"""Bounded asynchronous subprocess and ADB adapters."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path

from py_atv_remote.domain.preview import AdbIdentity, PreviewError


@dataclass(frozen=True, slots=True)
class Toolchain:
    adb: str
    scrcpy: str

    @classmethod
    def resolve(cls) -> Toolchain:
        bundled = Path(__file__).resolve().parents[1] / "vendor" / "linux-x86_64"

        def find(name: str) -> str:
            override = os.environ.get(f"PY_ATV_REMOTE_{name.upper()}")
            candidate = Path(override).expanduser() if override else bundled / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.resolve())
            if override:
                raise PreviewError(f"Caminho configurado para {name} inválido.")
            system = shutil.which(name)
            if system:
                return system
            raise PreviewError(f"{name} não encontrado. Verifique os componentes da instalação.")

        return cls(find("adb"), find("scrcpy"))

    async def validate(self) -> str:
        """Reject incompatible system tools before starting a stream."""
        version = await run_command(self.adb, "version", timeout=5)
        help_text = await run_command(self.scrcpy, "--help", timeout=5, output_limit=131072)
        for flag in ("--serial", "--no-audio", "--no-control", "--video-bit-rate", "--max-fps"):
            if flag not in help_text:
                raise PreviewError("scrcpy incompatível. Atualize ou use as ferramentas incluídas.")
        scrcpy_version = await run_command(self.scrcpy, "--version", timeout=5)
        return f"{version}\n{scrcpy_version}"


def validate_endpoint(endpoint: str) -> tuple[str, int]:
    """Validate IPv4 or DNS name and an explicit TCP port."""
    host, separator, port = endpoint.rpartition(":")
    if (
        not separator
        or len(host) > 253
        or not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", host)
        or not port.isascii()
        or not port.isdigit()
        or not 1 <= int(port) <= 65535
    ):
        raise PreviewError("Informe IP ou nome e porta válidos (1-65535). IPv6 não é suportado.")
    if all(c.isdigit() or c == "." for c in host):
        try:
            ipaddress.IPv4Address(host)
        except ValueError as exc:
            raise PreviewError("Endereço IPv4 inválido.") from exc
    elif any(
        not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
        for label in host.split(".")
    ):
        raise PreviewError("Nome de rede inválido.")
    return host, int(port)


async def terminate(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process.terminate()
        await asyncio.wait_for(process.wait(), 3)
    except ProcessLookupError:
        pass
    except TimeoutError:
        process.kill()
        await process.wait()


async def read_tail(stream: asyncio.StreamReader | None, limit: int = 8192) -> bytes:
    tail = b""
    if stream is not None:
        while chunk := await stream.read(4096):
            tail = (tail + chunk)[-limit:]
    return tail


async def run_command(
    executable: str,
    *args: str,
    code: str | None = None,
    timeout: float = 15,
    output_limit: int = 8192,
) -> str:
    """Run a bounded command and reap the child on every exit path."""
    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as exc:
        raise PreviewError("Não foi possível iniciar ADB.") from exc
    reader = asyncio.create_task(read_tail(process.stdout, output_limit))
    try:
        if process.stdin is not None:
            if code is not None:
                process.stdin.write((code + "\n").encode())
                await process.stdin.drain()
            process.stdin.close()
        await asyncio.wait_for(process.wait(), timeout)
        output = (await reader).decode(errors="replace")
    except TimeoutError as exc:
        raise PreviewError("ADB excedeu o tempo de espera. Verifique a TV e a rede.") from exc
    except (OSError, ConnectionError) as exc:
        raise PreviewError("A comunicação com ADB falhou.") from exc
    finally:
        await terminate(process)
        if not reader.done():
            reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)
    if code:
        output = output.replace(code, "[omitido]")
    if process.returncode or "failed" in output.lower() or "cannot connect" in output.lower():
        raise PreviewError(output.strip() or "Falha no ADB. Confira a autorização na TV.")
    return output.strip()


class AdbClient:
    """Use only explicit endpoints and serials, preserving the shared server."""

    def __init__(self, tools: Toolchain) -> None:
        self.tools = tools

    async def command(self, *args: str, code: str | None = None, timeout: float = 15) -> str:
        return await run_command(self.tools.adb, *args, code=code, timeout=timeout)

    async def pair(self, endpoint: str, code: str) -> None:
        validate_endpoint(endpoint)
        if len(code) != 6 or not code.isascii() or not code.isdigit():
            raise PreviewError("Informe os seis dígitos exibidos na TV.")
        await self.command("pair", endpoint, code=code, timeout=60)

    async def connect(self, endpoint: str) -> AdbIdentity:
        validate_endpoint(endpoint)
        await self.command("connect", endpoint)
        if await self.command("-s", endpoint, "get-state", timeout=5) != "device":
            raise PreviewError("TV offline ou não autorizada. Autorize este computador na TV.")
        serial = await self.command("-s", endpoint, "shell", "getprop", "ro.serialno", timeout=5)
        if not serial:
            serial = await self.command(
                "-s", endpoint, "shell", "getprop", "ro.boot.serialno", timeout=5
            )
        model = await self.command(
            "-s", endpoint, "shell", "getprop", "ro.product.model", timeout=5
        )
        if serial.lower() in {"unknown", "0123456789abcdef", "1234567890", "0"}:
            serial = ""
        return AdbIdentity(serial, model)

    @staticmethod
    def parse_mdns(output: str) -> list[str]:
        endpoints: list[str] = []
        for line in output.splitlines():
            fields = line.split()
            if len(fields) < 3 or fields[-2].rstrip(".") != "_adb-tls-connect._tcp":
                continue
            endpoint = fields[-1]
            try:
                validate_endpoint(endpoint)
            except PreviewError:
                continue
            if endpoint not in endpoints:
                endpoints.append(endpoint)
        return endpoints

    async def discover(self, host: str) -> list[str]:
        output = await self.command("mdns", "services", timeout=5)
        try:
            addresses = {
                item[4][0]
                for item in await asyncio.get_running_loop().getaddrinfo(
                    host, None, family=socket.AF_INET
                )
            }
        except OSError as exc:
            raise PreviewError("Não foi possível resolver o endereço da TV.") from exc
        return [
            endpoint
            for endpoint in self.parse_mdns(output)
            if endpoint.rpartition(":")[0] in addresses
        ]
