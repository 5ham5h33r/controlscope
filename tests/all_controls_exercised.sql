select r.control_id
from {{ ref('control_registry') }} r
left join {{ ref('mart_control_coverage') }} c using (control_id)
where coalesce(c.finding_count, 0) = 0
