{%- import 'modes.tpl' as modes with context -%}
{%- set levels = {
    "Morning": 14,
    "Day": 17,
    "Afternoon": 20,
    "Evening": 26,
    "Night": 30,
} -%}

{%- if modes.mode in levels -%}
{%- set start = levels[modes.mode] %}
{%- else -%}
{%- set start = 14 %}
{%- endif -%}

{%- set end = levels.get(modes.next, start) -%}
{{ modes.in_quad(start, end)|round|int }}
