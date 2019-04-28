import hyperion, time, math
from functools import partial

# Get the parameters
duration = float(hyperion.args.get('duration', 5.0))
interval = float(hyperion.args.get('interval', 0.00001))
method = hyperion.args.get('method', 'easeInOutQuad')
color_start = hyperion.args.get('color-start', (255,174,11))
color_end = hyperion.args.get('color-end', (100,100,100))
maintain_color = hyperion.args.get('maintain-end-color', True)

"""
Easing functions from https://easings.net/ and http://robertpenner.com/easing/
t: current time
b: beginning value
c: change in value
d: duration
"""

def linear(t, b, c, d):
    return int(round(t / d * (b + c)))

def inSine(t, b, c, d):
    return int(round(-c * math.cos(t / d * (math.pi / 2.0)) + c + b))

def inQuad(t, b, c, d):
    t = t / d
    return int(round(c * (t ** 2) + b))

def outQuad(t, b, c, d):
    t = t / d
    return int(round(-c * t * (t - 2) + b))

def easeInOutQuad(t, b, c, d):
    t = t / d * 2
    if t < 1:
        return int(round(c / 2 * t * t + b))
    return int(round(-c / 2 * ((t - 1) * (t - 3) - 1) + b))

def inExpo(t, b, c, d):
    if t == 0:
        return b
    return int(round(c * (2 ** (10 * (t / d - 1))) + b - c * 0.001))

def outQuart(t, b, c, d):
    t = t / d - 1
    return int(round(-c * (t*t*t*t - 1) + b))

def outCirc(t, b, c, d):
    t = t / d - 1
    return int(round(c * math.sqrt(1 - t * t) + b))



method = locals()[method]
red = partial(method, b=color_start[0], c=color_end[0] - color_start[0], d=duration)
green = partial(method, b=color_start[1], c=color_end[1] - color_start[1], d=duration)
blue = partial(method, b=color_start[2], c=color_end[2] - color_start[2], d=duration)
start = time.time()
prev_color = None
while not hyperion.abort():
    current = time.time() - start
    color = (red(current), green(current), blue(current))
    if color != prev_color:
        #print(color)
        hyperion.setColor(*color)
        prev_color = color
    time.sleep(interval)
    if current >= duration:
        break

hyperion.setColor(color_end[0], color_end[1], color_end[2])
while not hyperion.abort() and maintain_color:
    time.sleep(1)
