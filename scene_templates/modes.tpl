{%- set modes = {
    "Morning": {
        "start": "06:00:00",
        "end": "09:00:00",
    },
    "Day": {
        "start": "09:00:00",
        "end": "13:00:00",
    },
    "Afternoon": {
        "start": "13:00:00",
        "end": "18:00:00",
    },
    "Evening": {
        "start": "18:00:00",
        "end": "21:00:00",
    },
} -%}
{# Night has a start but an indeterminate end #}
{# Asleep has an indeterminate start/end #}

{%- set mode = states('input_select.myhome_mode') -%}
{%- if mode == 'Morning' -%}
    {%- set next = 'Day' -%}
{%- elif mode == 'Day' -%}
    {%- set next = 'Afternoon' -%}
{%- elif mode == 'Afternoon' -%}
    {%- set next = 'Evening' -%}
{%- elif mode == 'Evening' -%}
    {%- set next = 'Night' -%}
{%- elif mode == 'Night' -%}
    {%- set next = 'Asleep' -%}
{%- elif mode == 'Asleep' -%}
    {%- set next = 'Morning' -%}
{%- endif -%}

{%- if mode in modes -%}
    {%- set start = dt_util.dt.datetime.combine(dt_util.now(), dt_util.parse_time(modes[mode]["start"])) -%}
    {%- set end = dt_util.dt.datetime.combine(dt_util.now(), dt_util.parse_time(modes[mode]["end"])) -%}
    {%- set duration = (end - start).total_seconds() -%}
    {%- set current = (dt_util.now().replace(tzinfo=None) - start).total_seconds() -%}
{%- else -%}
    {%- set start = 0 -%}
    {%- set end = 0 -%}
    {%- set current = 1 -%}
    {%- set duration = 1 -%}
{%- endif -%}

{#-
    Helpers for easing functions between states
-#}
{%- import 'easing.tpl' as easing -%}
{% macro in_quad(b, e) -%}
    {%- set c = e - b -%}
    {{ easing.in_quad(current, b, c, duration) }}
{%- endmacro %}

{% macro in_out_quad(b, e) -%}
    {%- set c = e - b -%}
    {{ easing.in_out_quad(current, b, c, duration) }}
{%- endmacro %}

{% macro out_quad(b, e) -%}
    {%- set c = e - b -%}
    {{ easing.out_quad(current, b, c, duration) }}
{%- endmacro %}
