from __future__ import annotations

from kicad_mcp.models.component_contracts import find_component_contract


def test_find_component_contract_matches_exact_lib_id() -> None:
    contract = find_component_contract(lib_id="RF_Module:ESP32-S3-WROOM-1")

    assert contract is not None
    assert contract.key == "esp32_s3_wroom_1"


def test_find_component_contract_matches_footprint_pattern() -> None:
    contract = find_component_contract(footprint="Connector_USB:USB_C_Receptacle_GCT_USB4110")

    assert contract is not None
    assert contract.key == "usb_c_power_entry"


def test_find_component_contract_matches_ap2112k_exact_lib_id() -> None:
    contract = find_component_contract(lib_id="Regulator_Linear:AP2112K-3.3")

    assert contract is not None
    assert contract.key == "ap2112k_3v3"


def test_find_component_contract_does_not_match_generic_regulator_footprint() -> None:
    contract = find_component_contract(
        lib_id="Regulator_Linear:TPS7A20xxxDBV",
        footprint="Package_TO_SOT_SMD:SOT-23-5",
    )

    assert contract is None


def test_find_component_contract_returns_none_for_unknown_component() -> None:
    assert find_component_contract(lib_id="Device:R", footprint="Resistor_SMD:R_0805") is None


def test_find_component_contract_matches_new_seed_contract() -> None:
    contract = find_component_contract(lib_id="MCU_ST_STM32F1:STM32F103C8Tx")

    assert contract is not None
    assert contract.key == "stm32_mcu"
    assert contract.category == "mcu"
