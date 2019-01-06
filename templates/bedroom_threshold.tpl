{%- import 'modes.tpl' as modes with context -%}
{%- set levels = {
    "Morning": 3,
    "Day": 0,
    "Afternoon": 5,
    "Evening": 9,
    "Night": 9,
} -%}

{%- if modes.mode in levels -%}
{%- set start = levels[modes.mode] %}
{%- else -%}
{%- set start = 5 %}
{%- endif -%}

{%- set end = levels.get(modes.next, start) -%}
{{ modes.in_quad(start, end)|round|int }}
