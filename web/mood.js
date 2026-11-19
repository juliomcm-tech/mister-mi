/** Only confirmed production history can affect the analyst's expression. */
export function getAnalystMood(performance,settings={}){
 const normal={state:'neutral',label:'Critério antes de quantidade',note:'Posso concluir: nenhuma entrada.'};
 const stats=performance?.overall;
 if(!stats)return normal;
 const minimum=typeof settings.history_min_sample==='number'&&settings.history_min_sample>=30?settings.history_min_sample:30;
 const threshold=typeof settings.history_warning_roi==='number'&&Number.isFinite(settings.history_warning_roi)?Math.min(0,settings.history_warning_roi):-10;
 if(typeof stats.settled!=='number'||typeof stats.priced_settled!=='number'||stats.settled<minimum||stats.priced_settled<minimum
   ||typeof stats.odds_coverage!=='number'||stats.odds_coverage<80||typeof stats.paper_roi_pct!=='number'||!Number.isFinite(stats.paper_roi_pct))return normal;
 return stats.paper_roi_pct<threshold?{state:'review',label:'A rever o meu desempenho',note:'O histórico pede mais prudência.'}:normal;
}
