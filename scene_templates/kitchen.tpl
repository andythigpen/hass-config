{%- import 'modes.tpl' as modes with context -%}
{%- set lights = {
    "Morning": {
        "brightness": 255,
        "rgb_color": [255, 75, 0],
        "white_value": 120,
    },
    "Day": {
        "brightness": 255,
        "rgb_color": [255, 75, 20],
        "white_value": 255,
    },
    "Afternoon": {
        "brightness": 255,
        "rgb_color": [255, 75, 100],
        "white_value": 255,
    },
    "Evening": {
        "brightness": 255,
        "rgb_color": [255, 75, 0],
        "white_value": 75,
    },
    "Night": {
        "brightness": 200,
        "rgb_color": [255, 75, 0],
        "white_value": 50,
    },
} -%}
{%- if modes.mode in lights -%}
{%- set start = lights[modes.mode] -%}
{%- set end = lights.get(modes.next, start) -%}
light.rgbw_15_1: &light
  state: 'on'
  brightness: {{ modes.in_quad(start["brightness"], end["brightness"])|round|int }}
  rgb_color: [{{ modes.in_quad(start["rgb_color"][0], end["rgb_color"][0])|round|int }},
              {{ modes.in_quad(start["rgb_color"][1], end["rgb_color"][1])|round|int }},
              {{ modes.in_quad(start["rgb_color"][2], end["rgb_color"][2])|round|int }}]
  white_value: {{ modes.in_quad(start["white_value"], end["white_value"])|round|int }}
light.rgbw_15_2: *light
{%- endif -%}
