html = open('/home/safiankhaliq1/wtrlab/index.html').read()

# Find the result card template in JS and add WTR match info
# First check current result rendering code
idx = html.find('wtr_status')
print("Found wtr_status at:", idx)
print(html[idx-100:idx+400])
