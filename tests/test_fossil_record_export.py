from fossils.fossil_record_export import (
    GENESIS_TIMESTAMP,
    calculate_epoch,
    export_to_csv,
    normalize_arch,
)


def test_calculate_epoch_clamps_before_genesis_and_counts_day_windows():
    assert calculate_epoch(0) == 0
    assert calculate_epoch(GENESIS_TIMESTAMP - 1) == 0
    assert calculate_epoch(GENESIS_TIMESTAMP) == 0
    assert calculate_epoch(GENESIS_TIMESTAMP + 86400) == 1
    assert calculate_epoch(GENESIS_TIMESTAMP + (3 * 86400) + 123) == 3


def test_calculate_epoch_accepts_custom_genesis():
    assert calculate_epoch(1_700_172_799, genesis_timestamp=1_700_000_000) == 1
    assert calculate_epoch(1_699_999_999, genesis_timestamp=1_700_000_000) == 0


def test_normalize_arch_maps_aliases_case_insensitively():
    assert normalize_arch(" amd64 ") == "x86_64"
    assert normalize_arch("aarch64") == "ARM"
    assert normalize_arch("m2") == "Apple Silicon"
    assert normalize_arch("PowerPC") == "ppc64le"


def test_normalize_arch_handles_missing_and_unknown_values():
    assert normalize_arch("") == "unknown"
    assert normalize_arch(None) == "unknown"
    assert normalize_arch("riscv64") == "riscv64"


def test_export_to_csv_preserves_headers_and_quotes_strings(tmp_path):
    output = tmp_path / "history.csv"
    export_to_csv(
        [
            {
                "miner_id": "miner,with,commas",
                "epoch": 2,
                "device_arch": "G4",
            }
        ],
        str(output),
    )

    assert output.read_text() == (
        "miner_id,epoch,device_arch\n"
        '"miner,with,commas",2,"G4"\n'
    )
