{%- import 'modes.tpl' as modes with context -%}
{%- set levels = {
    "Morning": 2,
    "Day": 1,
    "Afternoon": 1,
    "Evening": 1,
    "Night": 2,
} -%}
{# overhead kitchen light on == 1, and hall light on == 2 #}

{%- if modes.mode in levels -%}
{%- set start = levels[modes.mode] %}
{%- else -%}
{%- set start = 5 %}
{%- endif -%}

{%- set end = levels.get(modes.next, start) -%}
{{ modes.in_quad(start, end)|round|int }}
