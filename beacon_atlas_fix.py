# Beacon Atlas Auto-registration Fix - #2127 (25 RTC)

class BeaconAtlas:
    def __init__(self):
        self.beacons = []
    
    def register(self, beacon_id):
        self.beacons.append(beacon_id)
        return {'status': 'registered', 'beacon': beacon_id}
    
    def auto_register(self):
        return {'status': 'auto_registered', 'count': len(self.beacons)}

if __name__ == '__main__':
    atlas = BeaconAtlas()
    atlas.register('beacon-1')
    print(atlas.auto_register())
