{%- import 'modes.tpl' as modes with context -%}
{%- set levels = {
    "Morning": 7,
    "Day": 2,
    "Afternoon": 3,
    "Evening": 14,
    "Night": 20,
} -%}

{%- if modes.mode in levels -%}
{%- set start = levels[modes.mode] %}
{%- else -%}
{%- set start = 7 %}
{%- endif -%}

{%- set end = levels.get(modes.next, start) -%}
{{ modes.in_quad(start, end)|round|int }}
