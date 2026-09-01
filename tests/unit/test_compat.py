"""Unit tests for compat.py — Protocol × Transport × Security compatibility engine.

Covers:
  - decompose/compose round-trip for all 8 legacy protocol strings
  - validate() accepts every real combination, rejects impossible ones
  - validate_fused() rejects unknown strings (no silent coercion)
  - sni_override_supported() truth table
  - matrix_view() declarative output
"""
import pytest

import compat


ALL_FUSED = [
    "vless-ws", "xhttp-packet-up", "xhttp-stream-up",
    "trojan-ws", "trojan-xhttp-packet-up", "trojan-xhttp-stream-up",
    "mtproto", "shadowsocks",
]


class TestRoundTrip:
    @pytest.mark.parametrize("fused", ALL_FUSED)
    def test_decompose_compose_round_trip(self, fused):
        p, t = compat.decompose(fused)
        assert compat.compose(p, t) == fused

    @pytest.mark.parametrize("fused", ALL_FUSED)
    def test_decompose_produces_valid_parts(self, fused):
        p, t = compat.decompose(fused)
        assert p in compat.PROTOCOLS
        assert (p, t) in compat.SERVER_RUNTIME

    def test_decompose_unknown_returns_raw(self):
        assert compat.decompose("vless-grpc") == ("vless-grpc", "")

    def test_decompose_empty(self):
        assert compat.decompose("") == ("", "")


class TestValidate:
    @pytest.mark.parametrize("fused", ALL_FUSED)
    def test_all_legacy_protocols_valid(self, fused):
        r = compat.validate_fused(fused)
        assert r.ok, f"{fused} should be valid: {r.reasons}"

    def test_valid_triple(self):
        r = compat.validate("vless", "ws", "tls")
        assert r.ok and r.protocol == "vless" and r.transport == "ws"

    def test_reject_unknown_protocol(self):
        r = compat.validate("vmess", "ws", "tls")
        assert not r.ok and any("vmess" in reason for reason in r.reasons)

    def test_reject_unknown_transport(self):
        r = compat.validate("vless", "grpc", "tls")
        assert not r.ok and any("transport" in reason for reason in r.reasons)

    def test_reject_unknown_security(self):
        r = compat.validate("vless", "ws", "reality")
        assert not r.ok and any("security" in reason for reason in r.reasons)

    def test_reject_reality_where_unsupported(self):
        # Reality needs xray-core; no server runtime here
        r = compat.validate("vless", "ws", "reality")
        assert not r.ok

    def test_reject_mtproto_with_ws(self):
        r = compat.validate("mtproto", "ws", "none")
        assert not r.ok

    def test_mtproto_tcp_none_valid(self):
        r = compat.validate("mtproto", "tcp", "none")
        assert r.ok

    def test_validate_never_raises_on_garbage(self):
        for proto in (None, "", 123, [], {"a": 1}):
            r = compat.validate(proto, "ws", "tls")  # type: ignore[arg-type]
            assert not r.ok and r.reasons

    def test_validate_fused_rejects_unknown_no_coercion(self):
        r = compat.validate_fused("vless-grpc")
        assert not r.ok and "no silent fallback" in r.reasons[0]


class TestSNIApplicability:
    def test_sni_supported_for_vless_ws(self):
        assert compat.sni_override_supported("vless-ws")

    def test_sni_supported_for_trojan_xhttp(self):
        assert compat.sni_override_supported("trojan-xhttp-stream-up")

    def test_sni_not_supported_for_shadowsocks(self):
        assert not compat.sni_override_supported("shadowsocks")

    def test_sni_not_supported_for_mtproto(self):
        assert not compat.sni_override_supported("mtproto")


class TestMatrixView:
    def test_matrix_lists_all_combinations(self):
        m = compat.matrix_view()
        assert len(m["combinations"]) == len(compat.SERVER_RUNTIME)
        assert set(m["protocols"]) == compat.PROTOCOLS
        assert "vless" in m["production"]
        assert "vmess" not in m["production"]

    def test_matrix_readiness_includes_beta_and_experimental(self):
        m = compat.matrix_view()
        assert m["readiness"]["wireguard"] == "BETA"
        assert m["readiness"]["hysteria2"] == "EXPERIMENTAL"

    def test_every_combo_carries_fused_string(self):
        for c in compat.matrix_view()["combinations"]:
            p, t = compat.decompose(c["fused"])
            assert (p, t) in compat.SERVER_RUNTIME
