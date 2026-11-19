export function canStartCollection(connection,token,health){return Boolean(connection?.apiBase&&token&&health?.configured===true);}
export function operationState(payload,{now=Date.now(),connection={},token='',health=null}={}){
 const canStart=canStartCollection(connection,token,health);
 const age=(now-new Date(payload?.updated_at).getTime())/60000;
 const stale=!Number.isFinite(age)||age>(payload?.settings?.max_age_minutes??45)||age < -1;
 const errors=(payload?.sources??[]).filter(s=>s.status==='error').length;
 const scheduler=payload?.pipeline_health?.scheduler_status??'unknown';
 const titles={not_observed:'Agendamento ainda sem execução verificada',overdue:'Agendamento em atraso',failed:'A última recolha agendada falhou',disabled:'Agendamento desativado',unavailable:'Estado do agendamento indisponível',unknown:'Estado do agendamento por confirmar',running:'Recolha agendada em curso',observed:'Recolha agendada verificada'};
 return {canStart,stale,errors,scheduler,level:stale?'stale':errors?'partial':'ready',
  title:stale?'É necessária uma nova recolha':errors?`Cobertura parcial · ${errors} fontes indisponíveis`:'Dados publicados disponíveis',
  message:canStart?'Podes iniciar uma nova recolha a partir desta app.':'O botão recarrega os dados publicados. Para executar o motor, abre o workflow no GitHub.',
  scheduleNote:titles[scheduler]??titles.unknown,refreshLabel:canStart?'Executar nova recolha':'Recarregar dados',heroLabel:canStart?'Executar análise':'Consultar análise'};
}
