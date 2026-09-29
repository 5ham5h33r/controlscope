with known_rows as (
    select concat('transactions/', transaction_id) as ref from {{ ref('stg_transactions') }}
    union all select concat('access_events/', event_id) from {{ ref('stg_access_events') }}
    union all select concat('vendors/', vendor_id) from {{ ref('stg_vendors') }}
    union all select concat('users/', user_id) from {{ ref('stg_users') }}
), exploded as (
    select f.finding_id, ref
    from {{ ref('mart_findings') }} f,
    unnest(json_value_array(f.evidence_refs)) as ref
)
select e.finding_id, e.ref
from exploded e left join known_rows k using (ref)
where k.ref is null
