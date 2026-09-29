with payments as (
    select * from {{ ref('stg_transactions') }} where payment_status = 'paid'
),
duplicate_invoices as (
    select vendor_id, invoice_id, any_value(business_unit) as business_unit,
           array_agg(concat('transactions/', transaction_id) order by transaction_id) as refs
    from payments group by vendor_id, invoice_id having count(*) > 1
),
privileged_logins as (
    select e.*, u.business_unit,
           lag(e.occurred_at) over (partition by e.user_id order by e.occurred_at, e.event_id) as prior_at,
           lag(e.event_id) over (partition by e.user_id order by e.occurred_at, e.event_id) as prior_id
    from {{ ref('stg_access_events') }} e
    join {{ ref('stg_users') }} u using (user_id)
    where e.event_type = 'login' and u.privileged
)
select 'duplicate_invoice' as control_id,
       concat(vendor_id, ':', invoice_id) as entity_id, business_unit,
       to_json_string(refs) as evidence_refs
from duplicate_invoices
union all
select 'split_payment', concat(vendor_id, ':', cast(paid_date as string)), business_unit,
       to_json_string(evidence_refs)
from {{ ref('int_payment_groups') }}
where payment_count > 1 and total_amount >= 10000
union all
select 'off_hours_payment', transaction_id, business_unit,
       to_json_string([concat('transactions/', transaction_id)])
from payments where extract(hour from paid_at at time zone 'UTC') < 6
   or extract(hour from paid_at at time zone 'UTC') >= 22
union all
select 'inactive_vendor_payment', p.transaction_id, p.business_unit,
       to_json_string([concat('transactions/', p.transaction_id), concat('vendors/', v.vendor_id)])
from payments p join {{ ref('stg_vendors') }} v using (vendor_id)
where not v.active
union all
select 'self_approval', transaction_id, business_unit,
       to_json_string([concat('transactions/', transaction_id)])
from payments where approver_id is not null and initiator_id = approver_id
union all
select 'missing_high_value_approval', transaction_id, business_unit,
       to_json_string([concat('transactions/', transaction_id)])
from payments where amount > 25000 and approver_id is null
union all
select 'terminated_user_login', e.event_id, u.business_unit,
       to_json_string([concat('access_events/', e.event_id), concat('users/', u.user_id)])
from {{ ref('stg_access_events') }} e
join {{ ref('stg_users') }} u using (user_id)
where e.event_type = 'login' and u.employment_status = 'terminated'
union all
select 'dormant_privileged_login', event_id, business_unit,
       to_json_string([concat('access_events/', prior_id),
                       concat('access_events/', event_id), concat('users/', user_id)])
from privileged_logins
where prior_at is not null and timestamp_diff(occurred_at, prior_at, day) >= 30
