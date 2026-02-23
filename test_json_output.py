#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from deprecated.old_miners.rustchain_universal_miner import UniversalMiner

# Create miner with json_mode=True
miner = UniversalMiner(miner_id='test-miner', json_mode=True)
# Call _emit
miner._emit('test', foo='bar', num=123)
# Call _print (should not print)
miner._print('This should not appear')
# Create another with json_mode=False
miner2 = UniversalMiner(miner_id='test-miner', json_mode=False)
miner2._print('This should appear')
miner2._emit('test', baz='qux')  # should not print
print("Test completed.")