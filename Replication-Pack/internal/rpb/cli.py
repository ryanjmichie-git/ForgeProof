from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from internal.rpb import exit_codes
from internal.rpb.models import VerificationResult
from internal.rpb.pack_loader import PackLoadError, load_pack_directory
from internal.rpb.pack_reader import PackReadError, extract_rpack
from internal.rpb.pack_writer import PackWriteError, create_rpack
from internal.rpb.runner import EvidenceRunError, run_test_commands
from internal.rpb.sign import SignError, write_signatures
from internal.rpb.staging import StagingError, apply_test_evidence, prepare_staging_directory
from internal.rpb.verify_signatures import recheck_tests, verify_pack_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rpb",
        description=(
            "Replication Pack Builder (RPB): build, inspect, and verify "
            "offline-verifiable replication packs."
        ),
        epilog="Run `rpb <subcommand> --help` for command-specific usage and examples.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser(
        "pack",
        help="Create a .rpack bundle from a directory.",
        description=(
            "Create a deterministic .rpack archive.\n"
            "- If input_dir already contains MANIFEST.json/HASHES.json/POLICY.json, it is treated as a staged pack root.\n"
            "- Otherwise input_dir is auto-staged under SOURCE/ and metadata files are generated."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pack_parser.add_argument(
        "input_dir",
        nargs="?",
        default=".",
        help="Directory to package (default: current directory).",
    )
    pack_parser.add_argument(
        "--output",
        default="out.rpack",
        help="Target pack filename (default: out.rpack).",
    )
    pack_parser.add_argument(
        "--sign-key",
        default=None,
        help="Path to raw 32-byte Ed25519 private key file for signing.",
    )
    pack_parser.add_argument(
        "--pubkey",
        default=None,
        help="Optional path to write derived 32-byte Ed25519 public key.",
    )
    pack_parser.add_argument(
        "--tests",
        action="append",
        default=[],
        help="Test command to run and capture as evidence (repeatable).",
    )
    pack_parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Skip test execution even when --tests is provided.",
    )
    pack_parser.set_defaults(handler=run_pack)

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify a .rpack bundle or unpacked directory (offline-first).",
        description=(
            "Offline verification checks signature validity, hash integrity, and policy compliance.\n"
            "Use --recheck to rerun manifest-declared test commands after offline checks pass."
        ),
        epilog=(
            "Verify exit codes:\n"
            "  0 = verification passed\n"
            "  2 = signature invalid\n"
            "  3 = hash mismatch / tampering\n"
            "  4 = policy violation / missing required elements\n"
            "  5 = recheck failed"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    verify_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Path to unpacked replication pack directory or .rpack archive.",
    )
    verify_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit verification report as JSON.",
    )
    verify_parser.add_argument(
        "--recheck",
        action="store_true",
        help="Rerun manifest-declared tests after offline verification passes.",
    )
    verify_parser.add_argument(
        "--pubkey",
        default=None,
        help="Path to raw 32-byte Ed25519 public key file. "
        "If omitted, SIGNATURES/signer-1.pub or signer metadata key is used.",
    )
    verify_parser.set_defaults(handler=run_verify)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect claims, evidence, and signer metadata."
    )
    inspect_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Path to unpacked replication pack directory or .rpack archive.",
    )
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit inspect report as JSON.",
    )
    inspect_parser.set_defaults(handler=run_inspect)

    return parser


def run_pack(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir).resolve()
    try:
        with tempfile.TemporaryDirectory(prefix="rpb-pack-") as temp_dir:
            staging = Path(temp_dir) / "staging"
            prepare_staging_directory(input_dir, staging)
            staged_pack = load_pack_directory(staging)

            test_commands: list[str] = []
            if not args.no_tests:
                test_commands = [item for item in args.tests if isinstance(item, str) and item.strip()]
            if test_commands:
                evidence_dir = staging / "EVIDENCE" / "TESTS"
                work_dir = staging / "SOURCE" if (staging / "SOURCE").exists() else staging
                results = run_test_commands(
                    test_commands,
                    work_dir=work_dir,
                    evidence_dir=evidence_dir,
                    stop_on_failure=True,
                    shell=True,
                )
                apply_test_evidence(staging, test_commands, results)
                staged_pack = load_pack_directory(staging)

            if args.sign_key:
                metadata = write_signatures(
                    staging_dir=staging,
                    private_key_path=args.sign_key,
                    pubkey_out=args.pubkey,
                )
                print(f"signed with key_id: {metadata['key_id']}")
            else:
                claims = staged_pack.manifest.get("claims")
                thresholds = staged_pack.policy.get("signature_thresholds")
                required_profiles: list[str] = []
                if isinstance(claims, list) and isinstance(thresholds, dict):
                    for claim in claims:
                        if not isinstance(claim, dict):
                            continue
                        profile = claim.get("profile")
                        if isinstance(profile, str) and isinstance(thresholds.get(profile), int):
                            if int(thresholds[profile]) > 0 and profile not in required_profiles:
                                required_profiles.append(profile)
                if required_profiles:
                    print(
                        "pack warning: policy requires signatures for claimed profiles "
                        f"{','.join(required_profiles)}; use --sign-key for verifiable output",
                        file=sys.stderr,
                    )

            out_path = create_rpack(staging, args.output)
            print(f"created pack: {out_path}")
            return exit_codes.VERIFY_PASSED
    except (PackWriteError, SignError, PackLoadError, StagingError, OSError, EvidenceRunError) as exc:
        print(f"pack error: {exc}", file=sys.stderr)
        return 1


def run_verify(args: argparse.Namespace) -> int:
    try:
        target = Path(args.target)
        if target.suffix.lower() == ".rpack":
            with tempfile.TemporaryDirectory(prefix="rpb-verify-") as temp_dir:
                extract_rpack(target, temp_dir)
                outcome = verify_pack_directory(temp_dir, pubkey_path=args.pubkey)
                if args.recheck and outcome.exit_code == exit_codes.VERIFY_PASSED:
                    recheck_failures = recheck_tests(temp_dir)
                    if recheck_failures:
                        outcome.result.verified = False
                        outcome.result.failed_checks.extend(recheck_failures)
                        outcome.exit_code = exit_codes.RECHECK_FAILED
        else:
            outcome = verify_pack_directory(target, pubkey_path=args.pubkey)
            if args.recheck and outcome.exit_code == exit_codes.VERIFY_PASSED:
                recheck_failures = recheck_tests(target)
                if recheck_failures:
                    outcome.result.verified = False
                    outcome.result.failed_checks.extend(recheck_failures)
                    outcome.exit_code = exit_codes.RECHECK_FAILED
    except (PackReadError, PackLoadError, OSError) as exc:
        result = VerificationResult(
            verified=False,
            failed_checks=[str(exc)],
            claims_verified=[],
            claims_rejected=[],
            signers=[],
        )
        if args.json_output:
            print(json.dumps(result.to_dict(), separators=(",", ":"), sort_keys=True))
        else:
            print(f"verify error: {exc}")
        return exit_codes.POLICY_VIOLATION

    result = outcome.result
    if args.json_output:
        print(json.dumps(result.to_dict(), separators=(",", ":"), sort_keys=True))
    else:
        print(f"verified: {result.verified}")
        if result.failed_checks:
            print(f"failed_checks: {', '.join(result.failed_checks)}")
        print(f"claims_verified: {len(result.claims_verified)}")
        print(f"claims_rejected: {len(result.claims_rejected)}")
        if result.signers:
            signer_summary_parts: list[str] = []
            for item in result.signers:
                if item.reason:
                    signer_summary_parts.append(f"{item.key_id}:{item.status}({item.reason})")
                else:
                    signer_summary_parts.append(f"{item.key_id}:{item.status}")
            signer_summary = ", ".join(signer_summary_parts)
            print(f"signers: {signer_summary}")
    return outcome.exit_code


def run_inspect(args: argparse.Namespace) -> int:
    try:
        target = Path(args.target)
        if target.suffix.lower() == ".rpack":
            with tempfile.TemporaryDirectory(prefix="rpb-inspect-") as temp_dir:
                extract_rpack(target, temp_dir)
                pack = load_pack_directory(temp_dir)
        else:
            pack = load_pack_directory(target)
    except (PackLoadError, PackReadError) as exc:
        print(f"inspect error: {exc}", file=sys.stderr)
        return exit_codes.POLICY_VIOLATION

    manifest = pack.manifest
    signing = manifest.get("signing")
    signers = []
    if isinstance(signing, dict):
        signer_entries = signing.get("signers", [])
        if isinstance(signer_entries, list):
            signers = signer_entries

    report = {
        "pack_id": manifest.get("pack_id"),
        "claims": manifest.get("claims", []),
        "evidence": manifest.get("evidence", []),
        "signers": signers,
    }
    if args.json_output:
        print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    else:
        print(f"pack_id: {report['pack_id']}")
        print(f"claims: {len(report['claims'])}")
        print(f"evidence: {len(report['evidence'])}")
        print(f"signers: {', '.join(report['signers']) if report['signers'] else '(none)'}")
    return exit_codes.VERIFY_PASSED


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
