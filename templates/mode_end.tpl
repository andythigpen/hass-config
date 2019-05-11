{%- set mode = states('input_select.myhome_mode') -%}
{%- if mode == 'Morning' -%}
    09:00:00
{%- elif mode == 'Day' -%}
    13:00:00
{%- elif mode == 'Afternoon' -%}
    18:00:00
{%- elif mode == 'Evening' -%}
    21:00:00
{%- else -%}
    0
{%- endif -%}
