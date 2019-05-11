{%- set mode = states('input_select.myhome_mode') -%}
{%- if mode == 'Morning' -%}
    06:00:00
{%- elif mode == 'Day' -%}
    09:00:00
{%- elif mode == 'Afternoon' -%}
    13:00:00
{%- elif mode == 'Evening' -%}
    18:00:00
{%- else -%}
    0
{%- endif -%}
