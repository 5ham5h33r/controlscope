with payments as (
    select * from {{ ref('stg_transactions') }} where payment_status = 'paid'
),
unit_median as (
    select distinct business_unit,
           percentile_cont(cast(amount as float64), 0.5) over (partition by business_unit) as median_amount
    from payments
),
unit_mad as (
    select distinct p.business_unit, m.median_amount,
           percentile_cont(abs(cast(p.amount as float64) - m.median_amount), 0.5)
             over (partition by p.business_unit) as mad
    from payments p join unit_median m using (business_unit)
),
daily as (
    select * from {{ ref('int_access_activity') }}
),
login_median as (
    select distinct percentile_cont(cast(login_count as float64), 0.5) over () as median_count
    from daily
),
login_mad as (
    select distinct m.median_count,
           percentile_cont(abs(cast(d.login_count as float64) - m.median_count), 0.5)
             over () as mad
    from daily d cross join login_median m
)
select 'amount_outlier' as control_id, p.transaction_id as entity_id, p.business_unit,
       to_json_string([concat('transactions/', p.transaction_id)]) as evidence_refs
from payments p join unit_mad m using (business_unit)
where m.mad > 0 and 0.6745 * (cast(p.amount as float64) - m.median_amount) / m.mad > 6
union all
select 'login_burst', concat(d.user_id, ':', cast(d.event_date as string)),
       u.business_unit, to_json_string(d.evidence_refs)
from daily d join {{ ref('stg_users') }} u using (user_id)
cross join login_mad m
where d.login_count >= m.median_count + 8
  and (m.mad = 0 or 0.6745 * (d.login_count - m.median_count) / m.mad > 6)
