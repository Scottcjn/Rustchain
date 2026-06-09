from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "bounties" / "issue-2312" / "src" / "marketplace.html").read_text(encoding="utf-8")


def test_esc_and_attr_helpers_exist():
    assert "function esc(v)" in HTML
    assert "function attr(v)" in HTML


def test_machine_fields_escaped():
    assert "${esc(m.name)}" in HTML
    assert "${esc(m.architecture)}" in HTML
    assert "${esc(m.cpu_model)}" in HTML


def test_onclick_attributes_escaped():
    assert "openBookingModal('${attr(m.machine_id)}')" in HTML
    assert "viewMachineDetails('${attr(m.machine_id)}')" in HTML


def test_leaderboard_fields_escaped():
    assert "${esc(entry.name)}" in HTML
    assert "${esc(entry.architecture)}" in HTML


def test_reservation_fields_escaped():
    assert "${esc(r.reservation_id)}" in HTML
    assert "${esc(r.machine_id)}" in HTML
    assert "${esc(r.status)}" in HTML
    assert "startSession('${attr(r.reservation_id)}')" in HTML
    assert "viewReceipt('${attr(r.reservation_id)}')" in HTML


def test_receipt_fields_escaped():
    assert "${esc(receipt.receipt_id)}" in HTML
    assert "${esc(receipt.session_id)}" in HTML
    assert "${esc(receipt.machine_passport_id)}" in HTML
    assert "${esc(receipt.compute_hash)}" in HTML
    assert "${esc(receipt.signature)}" in HTML

def test_no_raw_api_field_interpolations():
    assert '${m.name}</h3>' not in HTML
    assert '${m.architecture}</span>' not in HTML
    assert '${entry.name}</td>' not in HTML
    assert '${r.reservation_id}</strong>' not in HTML
    assert "openBookingModal('${m.machine_id}')" not in HTML
