{%- import 'modes.tpl' as modes with context -%}
{%- set lights = {
    "Morning": {
        "standing": {
            "brightness": 170,
            "xy_color": [0.4449, 0.4066],
            "media_diff": 90,
            "easing": "in_quad",
         },
        "tv": {
            "brightness": 1,
            "xy_color": [0.4449, 0.4066],
            "media_diff": 190,
            "easing": "in_quad",
        },
    },
    "Day": {
        "standing": {
            "brightness": 255,
            "xy_color": [0.4244, 0.3993],
            "media_diff": 100,
            "easing": "in_quad",
         },
        "tv": {
            "brightness": 50,
            "xy_color": [0.4244, 0.3993],
            "media_diff": 200,
            "easing": "in_out_quad",
        },
    },
    "Afternoon": {
        "standing": {
            "brightness": 255,
            "xy_color": [0.3763, 0.3741],
            "media_diff": 100,
            "easing": "in_quad",
         },
        "tv": {
            "brightness": 80,
            "xy_color": [0.3763, 0.3741],
            "media_diff": 200,
            "easing": "in_out_quad",
        },
    },
    "Evening": {
        "standing": {
            "brightness": 250,
            "xy_color": [0.4883, 0.4149],
            "media_diff": 90,
            "easing": "in_quad",
         },
        "tv": {
            "brightness": 220,
            "xy_color": [0.4883, 0.4149],
            "media_diff": 190,
            "easing": "out_quad",
        },
    },
    "Night": {
        "standing": {
            "brightness": 200,
            "xy_color": [0.5268, 0.4133],
            "media_diff": 60,
            "easing": "out_quad",
         },
        "tv": {
            "brightness": 100,
            "xy_color": [0.5268, 0.4133],
            "media_diff": 80,
            "easing": "out_quad",
        },
    },
} -%}
{%- if modes.mode in lights -%}
{%- set start = lights[modes.mode] -%}
{%- set end = lights.get(modes.next, start) -%}
{%- set media_mode = states('input_select.media_mode') -%}
{%- set state_standing = states('light.living_room_standing') -%}
{%- set state_tv = states('light.tv_left') -%}

{%- macro light_on(start, end) -%}
  {%- set easing = modes|attr(start["easing"]) -%}
  {%- set bri = easing(start["brightness"], end["brightness"])|round|int %}
  {%- set media_diff = easing(start["media_diff"], end["media_diff"])|round|int %}
  state: 'on'
  # easing: {{ easing }}
  # bri: {{ bri }}
  # media_diff: {{ media_diff }}
  brightness: {% if states('input_select.media_mode') == 'TV' %}{{ [bri - media_diff, 1]|max }}{% else %}{{ bri }}{% endif %}
  xy_color: [{{ easing(start["xy_color"][0], end["xy_color"][0]) }},
             {{ easing(start["xy_color"][1], end["xy_color"][1]) }}]
{%- endmacro -%}

light.living_room_standing:
  {% if media_mode == 'Movie' -%}
  state: 'off'
  {%- else -%}
  {{ light_on(start["standing"], end["standing"]) }}
  {%- endif %}
  {% if state_standing == 'on' -%}
  transition: 10
  {%- endif %}
light.tv_left: &tv
  {% if media_mode == 'Movie' -%}
  state: 'off'
  {%- else -%}
  {{ light_on(start["tv"], end["tv"]) }}
  {%- endif %}
  {% if state_tv == 'on' -%}
  transition: 10
  {%- endif %}
light.tv_right: *tv
{%- endif -%}
