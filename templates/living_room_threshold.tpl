{%- import 'modes.tpl' as modes with context -%}
{%- set levels = {
    "Morning": 30,
    "Day": 12,
    "Afternoon": 15,
    "Evening": 25,
    "Night": 31,
} -%}
{# overhead light on == 32 #}

{%- if modes.mode in levels -%}
{%- set start = levels[modes.mode] %}
{%- else -%}
{%- set start = 30 %}
{%- endif -%}

{%- set end = levels.get(modes.next, start) -%}
{{ modes.in_out_quad(start, end)|round|int }}
