with logins as (
    select * from {{ ref('stg_access_events') }} where event_type = 'login'
)
select user_id, date(occurred_at) as event_date, count(*) as login_count,
       array_agg(concat('access_events/', event_id) order by event_id) as evidence_refs
from logins
group by user_id, event_date
