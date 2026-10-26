"""Narrow, swappable HTTP TTS provider adapters."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol

from .config import ProviderConfig


class ProviderError(RuntimeError):
    """A credential-free provider transport or response failure."""


class ProviderUncertainError(ProviderError):
    """The request may have reached the provider and consumed quota."""


@dataclass(frozen=True)
class SynthesisRequest:
    text: str
    model: str
    voice: str
    style: str
    speed: float
    sample_rate: int
    format: str
    audio_config: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, str, Mapping[str, str], bytes, float], HttpResponse]


class TTSProvider(Protocol):
    def synthesize(self, request: SynthesisRequest) -> bytes: ...


def _urllib_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout: float,
) -> HttpResponse:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, dict(response.headers.items()), response.read())
    except urllib.error.HTTPError as exc:
        return HttpResponse(exc.code, dict(exc.headers.items()) if exc.headers else {}, exc.read())
    except (TimeoutError, socket.timeout) as exc:
        raise ProviderUncertainError(
            "provider request timed out; delivery and quota usage are uncertain"
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ProviderUncertainError(
                "provider request timed out; delivery and quota usage are uncertain"
            ) from exc
        raise ProviderError("provider request failed before a usable response was received") from exc


class _JsonAdapter:
    default_endpoint = "/"

    def __init__(
        self,
        *,
        base_url: str,
        endpoint: str | None,
        api_key: str,
        timeout_seconds: float,
        options: Mapping[str, object],
        transport: Transport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._endpoint = endpoint or self.default_endpoint
        if not self._endpoint.startswith("/"):
            self._endpoint = "/" + self._endpoint
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._options = options
        self._transport = transport or _urllib_transport

    def _post(self, headers: Mapping[str, str], payload: Mapping[str, object]) -> bytes:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            result = self._transport(
                "POST",
                self._base_url + self._endpoint,
                {"Content-Type": "application/json", "Accept": "audio/*", **headers},
                body,
                self._timeout,
            )
        except (TimeoutError, socket.timeout) as exc:
            raise ProviderUncertainError(
                "provider request timed out; delivery and quota usage are uncertain"
            ) from exc
        if result.status < 200 or result.status >= 300:
            raise ProviderError(f"provider request failed with HTTP {result.status}")
        if not result.body:
            raise ProviderError("provider returned an empty audio response")
        return result.body


class VoAIDialogueAdapter(_JsonAdapter):
    """Map canonical requests to VoAI's one-item dialogue contract."""

    default_endpoint = "/TTS/generate-dialogue"

    def synthesize(self, request: SynthesisRequest) -> bytes:
        if len(request.text) > 1000:
            raise ProviderError("VoAI dialogue text exceeds 1000 characters; shorten the source or segment")
        payload = {
            "input": {
                "dialogue": [
                    {
                        "voai_script_text": request.text,
                        "voice": {
                            "name": request.voice,
                            "style": request.style,
                            "version": request.model,
                        },
                        "audio_config": {**request.audio_config, "speed": request.speed},
                    }
                ]
            }
        }
        header_name = str(self._options.get("api_key_header", "x-api-key"))
        return self._post(
            {
                header_name: self._api_key,
                "x-output-format": request.format,
                "x-sample-rate": str(request.sample_rate),
            },
            payload,
        )


class OpenAISpeechAdapter(_JsonAdapter):
    """Map canonical requests to the OpenAI-compatible speech endpoint."""

    default_endpoint = "/v1/audio/speech"

    def synthesize(self, request: SynthesisRequest) -> bytes:
        payload: dict[str, object] = {
            "model": request.model,
            "input": request.text,
            "voice": request.voice,
            "speed": request.speed,
            "response_format": request.format,
        }
        if request.style:
            payload["instructions"] = request.style
        headers = {"Authorization": f"Bearer {self._api_key}"}
        sample_rate_header = self._options.get("sample_rate_header")
        if isinstance(sample_rate_header, str) and sample_rate_header.strip():
            headers[sample_rate_header.strip()] = str(request.sample_rate)
        return self._post(headers, payload)


def build_provider(
    config: ProviderConfig,
    api_key: str,
    *,
    transport: Transport | None = None,
) -> TTSProvider:
    adapters = {
        "voai_dialogue": VoAIDialogueAdapter,
        "openai_speech": OpenAISpeechAdapter,
    }
    adapter = adapters.get(config.name)
    if adapter is None:
        raise ProviderError(f"unsupported provider adapter '{config.name}'")
    return adapter(
        base_url=config.base_url,
        endpoint=config.endpoint,
        api_key=api_key,
        timeout_seconds=config.timeout_seconds,
        options=config.options,
        transport=transport,
    )
