{%- import 'modes.tpl' as modes with context -%}
{%- set lights = {
    "Day": {
        "brightness": 255,
        "easing": "in_quad",
    },
    "Afternoon": {
        "brightness": 255,
        "easing": "in_quad",
    },
    "Evening": {
        "brightness": 200,
        "easing": "in_quad",
    },
    "Night": {
        "brightness": 150,
        "easing": "out_quad",
    },
} -%}
{%- if modes.mode in lights -%}
{%- set still_asleep = modes.mode == "Day" and states("binary_sensor.bed_sensor_16_1") == "on" -%}
{%- set is_bedtime = states("script.bedtime") == "on" or states("script.bedtime_now") == "on" -%}
{%- if not is_bedtime and not still_asleep -%}
{%- set start = lights[modes.mode] -%}
{%- set end = lights.get(modes.next, start) -%}
{%- set easing = modes|attr(start["easing"]) -%}
light.night_stand: &light
  state: 'on'
  brightness: {{ easing(start["brightness"], end["brightness"])|round|int }}
light.dresser: *light
{%- endif -%}
{%- endif -%}
