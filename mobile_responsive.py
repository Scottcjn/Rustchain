# BoTTube Mobile Responsive Polish - #2160 (15 RTC)

class MobileResponsive:
    def __init__(self):
        self.breakpoints = {'mobile': 768, 'tablet': 1024, 'desktop': 1920}
    
    def get_layout(self, width):
        if width < self.breakpoints['mobile']:
            return 'mobile'
        elif width < self.breakpoints['tablet']:
            return 'tablet'
        else:
            return 'desktop'

if __name__ == '__main__':
    responsive = MobileResponsive()
    print(responsive.get_layout(500))
