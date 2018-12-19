{%- import 'modes.tpl' as modes with context -%}
{%- set lights = {
    "Morning": {
        "brightness": 120,
    },
    "Day": {
        "brightness": 175,
    },
    "Afternoon": {
        "brightness": 175,
    },
    "Evening": {
        "brightness": 100,
    },
    "Night": {
        "brightness": 50,
    },
} -%}
{%- if modes.mode in lights -%}
{%- set start = lights[modes.mode] -%}
{%- set end = lights.get(modes.next, start) -%}
light.hall:
  state: 'on'
  brightness: {{ modes.in_quad(start["brightness"], end["brightness"])|round|int }}
{%- endif -%}
