{%- set mode = states('input_select.myhome_mode') -%}
{%- if mode == 'Morning' -%}
    Day
{%- elif mode == 'Day' -%}
    Afternoon
{%- elif mode == 'Afternoon' -%}
    Evening
{%- elif mode == 'Evening' -%}
    Night
{%- elif mode == 'Night' -%}
    Asleep
{%- elif mode == 'Asleep' -%}
    Morning
{%- endif -%}
