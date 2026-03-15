#!/usr/bin/env python3
"""RustChain Mining ROI Calculator — Estimate return on vintage hardware investment."""
import sys

HARDWARE = {
    "ibook-g3": {"cost": 30, "watts": 25, "mult": 1.5, "name": "iBook G3"},
    "imac-g4": {"cost": 50, "watts": 40, "mult": 2.5, "name": "iMac G4"},
    "powermac-g4": {"cost": 40, "watts": 60, "mult": 2.5, "name": "Power Mac G4"},
    "powermac-g5": {"cost": 80, "watts": 180, "mult": 4.0, "name": "Power Mac G5"},
    "macmini-g4": {"cost": 35, "watts": 30, "mult": 2.5, "name": "Mac Mini G4"},
    "thinkpad-x86": {"cost": 20, "watts": 35, "mult": 1.0, "name": "ThinkPad x86"},
    "rpi4": {"cost": 45, "watts": 5, "mult": 1.0, "name": "Raspberry Pi 4"},
}

def calculate(hw_key, electricity_kwh=0.12, rtc_price=0.10, base_reward=0.5):
    hw = HARDWARE.get(hw_key, HARDWARE["thinkpad-x86"])
    daily_reward = base_reward * hw["mult"] * 24
    daily_revenue = daily_reward * rtc_price
    daily_electricity = (hw["watts"] / 1000) * 24 * electricity_kwh
    daily_profit = daily_revenue - daily_electricity
    breakeven = hw["cost"] / daily_profit if daily_profit > 0 else float('inf')
    
    print(f"RustChain Mining ROI — {hw['name']}")
    print("=" * 45)
    print(f"Hardware Cost:    ${hw['cost']}")
    print(f"Power Draw:       {hw['watts']}W")
    print(f"Multiplier:       {hw['mult']}x")
    print(f"Daily RTC:        {daily_reward:.2f} RTC")
    print(f"Daily Revenue:    ${daily_revenue:.4f}")
    print(f"Daily Electricity:${daily_electricity:.4f}")
    print(f"Daily Profit:     ${daily_profit:.4f}")
    print(f"Breakeven:        {breakeven:.0f} days")
    print(f"\nMonthly Profit:   ${daily_profit * 30:.2f}")
    print(f"Annual Profit:    ${daily_profit * 365:.2f}")
    print(f"Annual ROI:       {(daily_profit * 365 / hw['cost'] * 100):.0f}%")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        calculate(sys.argv[1])
    else:
        print("Available hardware:\n")
        for k, v in HARDWARE.items():
            print(f"  {k:<15} ${v['cost']:>3} | {v['watts']:>3}W | {v['mult']}x | {v['name']}")
        print(f"\nUsage: python roi_calculator.py <hardware-key>")
