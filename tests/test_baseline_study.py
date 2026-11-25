import json

import numpy as np
import pandas as pd
import pytest

from coffee_dw import baseline_study as study
from coffee_dw.forecast import evaluate_monthly


@pytest.fixture(scope='module')
def prepared():
    return study.prepare_inputs(study.SOURCE_PATH)


def test_phases_match_existing_reference_exactly(prepared):
    monthly=prepared[0]
    reference,_,future,summary=evaluate_monthly(monthly)
    results=[]
    for split,n in [('validation',72),('test',36)]:
        predictions,metrics,origins,audit=study.evaluate_phase(monthly,split)
        assert len(predictions)==n
        assert predictions.TrainEnd.lt(predictions.ForecastMonth).all()
        assert (origins.loc[origins.ModelName.eq('ridge'),'EffectiveFitN'] == origins.loc[origins.ModelName.eq('ridge'),'HistoryN']-3).all()
        assert len(audit)==n
        results.append(predictions)
    actual=pd.concat(results,ignore_index=True).sort_values(['Market','ForecastMonth','ModelName']).reset_index(drop=True)
    expected=reference.sort_values(['Market','ForecastMonth','ModelName']).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual[expected.columns],expected)


def test_test_mutation_cannot_change_validation_selection_or_first_test_forecast(prepared):
    monthly=prepared[0]
    before,metrics,_,_=study.evaluate_phase(monthly,'validation')
    changed=monthly.copy()
    changed.loc[changed.MonthStart.ge('2013-10-01'),'Sales']+=100000
    after,altered_metrics,_,_=study.evaluate_phase(changed,'validation')
    pd.testing.assert_frame_equal(before,after)
    assert study.choose_method(metrics)[0]==study.choose_method(altered_metrics)[0]=='moving_average_3'
    test_before=study.evaluate_phase(monthly,'test')[0]
    test_after=study.evaluate_phase(changed,'test')[0]
    np.testing.assert_allclose(test_before.loc[test_before.ForecastMonth.eq('2013-10-01'),'Prediction'],
                               test_after.loc[test_after.ForecastMonth.eq('2013-10-01'),'Prediction'])


def test_selection_rejects_test_metrics(prepared):
    metrics=study.evaluate_phase(prepared[0],'test')[1]
    with pytest.raises(ValueError,match='validation'):
        study.choose_method(metrics)


def test_scaler_audit_matches_only_first_origin_training_features(prepared):
    monthly,features,*_=prepared
    audit=study.evaluate_phase(monthly,'validation')[3]
    first=audit.loc[audit.ForecastMonth.eq('2013-04-01')]
    for row in first.itertuples():
        samples=features.loc[features.Market.eq(row.Market)&features.Split.eq('initial_history')&features.CompleteLag123]
        values=samples[row.Feature.capitalize()]
        assert row.FitN==12
        assert row.MeanTrain==pytest.approx(values.mean())
        assert row.ScaleTrain==pytest.approx(values.std(ddof=0))


def test_selection_file_exists_before_test_and_future_has_no_fake_actual(tmp_path,monkeypatch):
    real=study.evaluate_phase
    stages=[]
    def checked(monthly,split):
        if split=='test':
            decision=json.loads((tmp_path/'03_validation/selection.json').read_text(encoding='utf-8'))
            assert decision['selected_method']=='moving_average_3'
            assert decision['test_used_for_this_selection'] is False
        stages.append(split)
        return real(monthly,split)
    monkeypatch.setattr(study,'evaluate_phase',checked)
    result=study.run_study(output=tmp_path,render=False)
    assert stages==['validation','test']
    assert (result['validation_predictions'],result['test_predictions'],result['future_predictions'])==(72,36,4)
    assert result['source']['sha256']==result['source_sha256_after']
    future=pd.read_csv(tmp_path/'05_future/next_month.csv')
    assert future.Actual.isna().all()
    state=json.loads((tmp_path/'05_future/selected_state.json').read_text(encoding='utf-8'))
    for market in state['markets']:
        expected=np.mean([x['sales'] for x in market['observations_for_rule']])
        assert future.loc[future.Market.eq(market['Market']),'Prediction'].iloc[0]==pytest.approx(expected)
    events=pd.read_csv(tmp_path/'06_summary/execution_events.csv')
    assert events.loc[events.Stage.eq('selection_saved'),'Sequence'].iloc[0] < events.loc[events.Stage.eq('test_started'),'Sequence'].iloc[0]


def test_mape_excludes_zero_actual_without_losing_mae_observation():
    frame=pd.DataFrame({'Market':['West','West'],'ModelName':['naive_last','naive_last'],
                        'Split':['validation','validation'],'Actual':[0.,100.],'Prediction':[50.,90.]})
    metrics=study.score(frame).loc[lambda x:x.Market.eq('ALL')].iloc[0]
    assert metrics.N==2 and metrics.MAPE_N==1
    assert metrics.MAE==30 and metrics.MAPE==10
    assert np.isnan(study.error_table(frame).APE.iloc[0])


def test_missing_month_is_not_silently_imputed(prepared):
    with pytest.raises(ValueError,match='đủ 24 tháng'):
        study.validate_monthly(prepared[0].drop(index=0))
