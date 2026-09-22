from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from modules.shared import ingestion_observability as telemetry


def connection(monkeypatch, rows=None, aggregate=None):
    c=Mock()
    c.scalar.return_value=1
    if aggregate is not None: c.execute.return_value.mappings.return_value.one.return_value=aggregate
    else: c.execute.return_value.mappings.return_value.all.return_value=rows
    engine=Mock(); engine.connect.return_value.__enter__=Mock(return_value=c); engine.connect.return_value.__exit__=Mock()
    monkeypatch.setattr(telemetry,'database_engine',lambda _:engine)
    return c


def test_local_day_and_real_zero(monkeypatch):
    c=connection(monkeypatch,aggregate={'validated_today':0,'duplicates':0,'recent_bytes':0})
    summary=telemetry.ingestion_summary('Asia/Kolkata')
    assert summary['validated_today']==0 and summary['recent_mib_per_second']==0.0
    params=c.execute.call_args.args[1]
    assert params['start'].hour==18 and params['start'].minute==30
    assert (params['now']-params['recent']).total_seconds()==60


def test_bad_timezone_is_validation_error():
    with pytest.raises(HTTPException) as error: telemetry.ingestion_summary('unknown/timezone')
    assert error.value.status_code==422


def test_pipeline_does_not_call_queued_missing_or_failed_completed(monkeypatch):
    rows=[{'document_id':uuid4(),'status':status,'current_stage':None,'stage_results':stage,
           'error_message':err,'embedding_status':indexed,'published':published}
          for status,stage,err,indexed,published in [
          ('partial',{'ocr_extraction':{'status':'completed'}},None,'INDEXED',True),
          ('in_progress',{'ocr_extraction':{'status':'started'}},None,None,False),
          (None,None,None,None,None),
          ('failed_terminal',{'ocr_extraction':{'status':'failed'}},'Source read failed',None,False)]]
    connection(monkeypatch,rows=rows)
    result=telemetry.run_pipeline(uuid4())
    assert result['canonical_documents']==4 and result['indexed']==1 and result['published']==1
    assert result['ai_statuses']['awaiting_delivery']==1
    assert result['extraction']=={'completed':1,'started':1,'pending':1,'failed':1}
    assert len(result['errors'])==1
