{%- import 'modes.tpl' as modes with context -%}
{%- set levels = {
    "Morning": 30,
    "Day": 22,
    "Afternoon": 25,
    "Evening": 30,
    "Night": 30,
} -%}

{%- if modes.mode in levels -%}
{%- set start = levels[modes.mode] %}
{%- else -%}
{%- set start = 25 %}
{%- endif -%}

{%- set end = levels.get(modes.next, start) -%}
{{ modes.in_quad(start, end)|round|int }}
