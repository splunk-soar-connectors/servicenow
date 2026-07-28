# Copyright (c) 2026 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from src.actions import on_poll as on_poll_module


def test_on_poll_strips_format_controls_from_ingested_ticket_data(
    collect_on_poll_outputs, poll_asset_factory
):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case\u202e title",
        "description": "Description\u200d text",
        "sys_updated_on": "2026-01-02 03:04:05",
    }

    outputs, _calls = collect_on_poll_outputs([issue], poll_asset_factory())

    container = outputs[0]
    primary_artifact = outputs[1]
    assert container.name == "Case title"
    assert container.data["description"] == "Description text"
    assert primary_artifact.cef["short_description"] == "Case title"


def test_on_poll_extracts_internationalized_urls(
    collect_on_poll_outputs, poll_asset_factory
):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": "Review http://例え.テスト/パス",
        "sys_updated_on": "2026-01-02 03:04:05",
    }

    outputs, _calls = collect_on_poll_outputs(
        [issue],
        poll_asset_factory(extract_urls=True),
    )

    url_artifacts = [item for item in outputs if getattr(item, "label", None) == "URL"]
    assert [item.cef["URL"] for item in url_artifacts] == ["http://例え.テスト/パス"]
    assert [item.cef_types for item in url_artifacts] == [{"URL": ["url"]}]


def test_on_poll_validates_ips_and_scans_text_values_only(
    collect_on_poll_outputs, poll_asset_factory
):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": (
            "valid 192.0.2.10 invalid 999.999.999.999 ipv6 2001:db8::1%eth0"
        ),
        "198.51.100.77": True,
        "sys_updated_on": "2026-01-02 03:04:05",
    }

    outputs, _calls = collect_on_poll_outputs(
        [issue],
        poll_asset_factory(extract_ips=True),
    )

    ipv4s = [
        item.cef["ip_address"]
        for item in outputs
        if getattr(item, "label", None) == "IP Address"
    ]
    ipv6s = [
        item.cef["ipv6_address"]
        for item in outputs
        if getattr(item, "label", None) == "IPV6 Address"
    ]
    assert ipv4s == ["192.0.2.10"]
    assert ipv6s == ["2001:db8::1"]
    assert [
        item.cef_types
        for item in outputs
        if getattr(item, "label", None) == "IP Address"
    ] == [{"ip_address": ["ip"]}]
    assert [
        item.cef_types
        for item in outputs
        if getattr(item, "label", None) == "IPV6 Address"
    ] == [{"ipv6_address": ["ip"]}]


def test_on_poll_extracts_supported_hashes(collect_on_poll_outputs, poll_asset_factory):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": (
            "md5 d41d8cd98f00b204e9800998ecf8427e "  # pragma: allowlist secret
            "sha1 da39a3ee5e6b4b0d3255bfef95601890afd80709 "  # pragma: allowlist secret
            "sha256 e3b0c44298fc1c149afbf4c8996fb924"
            "27ae41e4649b934ca495991b7852b855"  # pragma: allowlist secret
        ),
        "sys_updated_on": "2026-01-02 03:04:05",
    }

    outputs, _calls = collect_on_poll_outputs(
        [issue],
        poll_asset_factory(extract_hashes=True),
    )

    hash_artifacts = [
        item for item in outputs if getattr(item, "label", None) == "Hash"
    ]
    assert (
        [item.cef["hash"] for item in hash_artifacts]
        == [
            "d41d8cd98f00b204e9800998ecf8427e",  # pragma: allowlist secret
            "da39a3ee5e6b4b0d3255bfef95601890afd80709",  # pragma: allowlist secret
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # pragma: allowlist secret
        ]
    )
    assert [item.cef_types for item in hash_artifacts] == [
        {"hash": ["hash"]},
        {"hash": ["hash"]},
        {"hash": ["hash"]},
    ]


def test_on_poll_preserves_configured_timezone_for_checkpoint(
    collect_on_poll_outputs, poll_asset_factory
):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": "Description",
        "sys_updated_on": "2026-01-02 03:04:05",
    }
    asset = poll_asset_factory(timezone=ZoneInfo("Asia/Kolkata"))

    _outputs, calls = collect_on_poll_outputs([issue], asset)

    assert calls[0]["payload"]["sysparm_query"] == (
        "ORDERBYsys_updated_on"
        "^sys_updated_on>=javascript:gs.dateGenerate('2026-01-02','03:04:05')"
    )
    assert asset.ingest_state["last_time"] == "2026-01-02 08:34:05"


def test_on_poll_uses_raw_utc_checkpoint_without_configured_timezone(
    collect_on_poll_outputs, poll_asset_factory
):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": "Description",
        "sys_updated_on": "2026-01-02 03:04:05",
    }
    asset = poll_asset_factory(timezone=None)

    _outputs, calls = collect_on_poll_outputs([issue], asset)

    assert calls[0]["payload"]["sysparm_query"] == (
        "ORDERBYsys_updated_on^sys_updated_on>=2026-01-02 03:04:05"
    )
    assert asset.ingest_state["last_time"] == "2026-01-02 03:04:05"


def test_on_poll_defers_first_run_state_until_generator_is_exhausted(
    monkeypatch, poll_asset_factory
):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": "Description",
        "sys_updated_on": "2026-01-02 03:04:05",
    }
    asset = poll_asset_factory(
        ingest_state={"last_time": "2026-01-01 00:00:00", "first_run": True}
    )

    class FakeServiceNowClient:
        def __init__(self, asset):
            self.asset = asset

        def paginator(self, endpoint, *, payload, limit):
            return [issue]

    class FakeSoar:
        def get(self, endpoint):
            return SimpleNamespace(
                json=lambda: {
                    "severity": [
                        {"name": "medium", "is_default": True},
                    ]
                }
            )

    params = SimpleNamespace(is_manual_poll=lambda: False)
    monkeypatch.setattr(on_poll_module, "ServiceNowClient", FakeServiceNowClient)

    generator = on_poll_module.on_poll.__wrapped__(params, FakeSoar(), asset)
    next(generator)
    assert asset.ingest_state["first_run"] is True

    list(generator)
    assert asset.ingest_state["first_run"] is False
