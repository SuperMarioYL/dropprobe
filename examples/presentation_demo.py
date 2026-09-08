"""Compare static card assembly for two declared CPU memory profiles; no inference."""
import json
from dropprobe.config_db import ConfigDB,DropConfig,QuantSpec,BackendSpec
from dropprobe.drops import Drop
from dropprobe.hardware import HardwareProfile
from dropprobe.probe import build_probe_card,probe_drop
model='example/local-model'
drop=Drop(model,'Example','example','2026-01-01')
db=ConfigDB({model:DropConfig(model,(QuantSpec('Q4',4.0,'example/quant'),QuantSpec('Q8',8.0,'example/quant')),BackendSpec('example/engine','demo-ref'),4096)})
rows=[]
for ram in [8.0,2.0]:
    hardware=HardwareProfile(0.0,ram,20.0,'cpu')
    probe=probe_drop(drop,hardware,db)
    card=build_probe_card(drop,hardware,db,probe)
    rows.append({'declared_ram_gb':ram,'selected_quant':card.quant.name,
                 'runnable_field':card.runnable,'probe_status':probe.status.value,
                 'smoke_probe_ok':card.smoke_probe_ok})
print(json.dumps(rows,indent=2))
assert rows[0]['runnable_field'] is True and rows[1]['runnable_field'] is None
assert all(row['smoke_probe_ok'] is None for row in rows)
