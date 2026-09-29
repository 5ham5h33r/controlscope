select r.control_id, r.control_version, r.kind, r.description,
       count(f.finding_id) as finding_count,
       countif(f.risk_score >= 80) as high_risk_count
from {{ ref('control_registry') }} r
left join {{ ref('mart_findings') }} f using (control_id)
group by r.control_id, r.control_version, r.kind, r.description
