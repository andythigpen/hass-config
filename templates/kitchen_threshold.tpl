{%- import 'modes.tpl' as modes with context -%}
{%- set levels = {
    "Morning": 30,
    "Day": 18,
    "Afternoon": 22,
    "Evening": 25,
    "Night": 30,
} -%}
{# overhead light on == 13 #}

{%- if modes.mode in levels -%}
{%- set start = levels[modes.mode] %}
{%- else -%}
{%- set start = 25 %}
{%- endif -%}

{%- set end = levels.get(modes.next, start) -%}
{{ modes.in_out_quad(start, end)|round|int }}
