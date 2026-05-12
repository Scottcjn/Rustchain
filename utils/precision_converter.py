"""
Fix float precision loss in amount conversion
Use Decimal for accurate financial calculations
"""
from decimal import Decimal, getcontext
from typing import Union, Dict, List
import json


class PrecisionConverter:
    """Handle precise amount conversions using Decimal"""
    
    def __init__(self, precision: int = 9):
        # Set precision for Decimal operations
        getcontext().prec = precision + 10  # Extra precision for intermediate calculations
        self.precision = precision
        self.rtc_decimals = Decimal(10) ** -precision  # Smallest RTC unit
    
    def rtc_to_nanortc(self, rtc_amount: Union[int, str, Decimal]) -> int:
        """Convert RTC to nanoRTC (1 RTC = 10^9 nanoRTC)
        
        Args:
            rtc_amount: Amount in RTC (can be int, string, or Decimal)
            
        Returns:
            int: Amount in nanoRTC
        """
        rtc = Decimal(str(rtc_amount))  # Convert to Decimal to avoid float errors
        nanortc = rtc * (Decimal(10) ** 9)
        
        # Use quantize to handle rounding properly
        nanortc = nanortc.quantize(Decimal('1'), rounding='ROUND_DOWN')
        
        return int(nanortc)
    
    def nanortc_to_rtc(self, nanortc_amount: Union[int, str, Decimal]) -> Decimal:
        """Convert nanoRTC to RTC
        
        Args:
            nanortc_amount: Amount in nanoRTC (can be int, string, or Decimal)
            
        Returns:
            Decimal: Amount in RTC
        """
        nanortc = Decimal(str(nanortc_amount))
        rtc = nanortc / (Decimal(10) ** 9)
        
        # Normalize to remove trailing zeros
        return rtc.normalize()
    
    def calculate_reward(self, base_reward: Union[int, str, Decimal], 
                        bonus: Union[int, str, Decimal] = 0,
                        multiplier: Union[int, str, Decimal] = 1) -> Dict:
        """Calculate reward with precise Decimal arithmetic
        
        Args:
            base_reward: Base reward in nanoRTC
            bonus: Bonus in nanoRTC
            multiplier: Multiplier (can be fractional)
            
        Returns:
            dict: Reward breakdown
        """
        base = Decimal(str(base_reward))
        bonus_dec = Decimal(str(bonus))
        mult = Decimal(str(multiplier))
        
        total = (base + bonus_dec) * mult
        total = total.quantize(Decimal('1'), rounding='ROUND_DOWN')
        
        return {
            'base_nanortc': int(base),
            'bonus_nanortc': int(bonus_dec),
            'multiplier': float(mult),
            'total_nanortc': int(total),
            'total_rtc': str(self.nanortc_to_rtc(total))
        }
    
    def batch_convert(self, amounts: List[Union[int, str, Decimal]], 
                     from_unit: str = 'rtc') -> List[int]:
        """Batch convert amounts with precise arithmetic
        
        Args:
            amounts: List of amounts
            from_unit: 'rtc' or 'nanortc'
            
        Returns:
            list: Converted amounts
        """
        results = []
        
        for amount in amounts:
            if from_unit == 'rtc':
                results.append(self.rtc_to_nanortc(amount))
            elif from_unit == 'nanortc':
                results.append(self.nanortc_to_rtc(amount))
            else:
                raise ValueError(f"Unknown unit: {from_unit}")
        
        return results


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Precision Converter for RTC/nanoRTC')
    parser.add_argument('--rtc-to-nano', type=str, help='Convert RTC to nanoRTC')
    parser.add_argument('--nano-to-rtc', type=str, help='Convert nanoRTC to RTC')
    parser.add_argument('--batch', action='store_true', help='Batch convert')
    
    args = parser.parse_args()
    
    converter = PrecisionConverter()
    
    if args.rtc_to_nano:
        result = converter.rtc_to_nanortc(args.rtc_to_nano)
        print(f"{args.rtc_to_nano} RTC = {result} nanoRTC")
    elif args.nano_to_rtc:
        result = converter.nanortc_to_rtc(args.nano_to_rtc)
        print(f"{args.nano_to_rtc} nanoRTC = {result} RTC")
    elif args.batch:
        # Demo batch conversion
        amounts = ['1.123456789', '2.987654321', '0.000000001']
        print("Batch converting RTC to nanoRTC:")
        results = converter.batch_convert(amounts, from_unit='rtc')
        for amt, res in zip(amounts, results):
            print(f"  {amt} RTC = {res} nanoRTC")
    else:
        print("Please provide --rtc-to-nano , --nano-to-rtc, or --batch")


if __name__ == '__main__':
    main()
