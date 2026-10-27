#!/usr/bin/env node
/**
 * Consulta de diagnóstico à API ANA HidroWebService.
 * Credenciais são lidas SOMENTE do ambiente e nunca exibidas.
 * Não substitui nem altera o feed público até validação científica.
 * Uso: configure secrets ANA_IDENTIFICADOR e ANA_SENHA; rode pelo GitHub Actions com código de estação
 */
const BASE='https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas';
const code=process.argv[2] || '66070004';
if(!/^\d{7,10}$/.test(code)){console.error('Código de estação inválido');process.exit(2);}
const id=process.env.ANA_IDENTIFICADOR, password=process.env.ANA_SENHA;
if(!id||!password){console.error('Defina ANA_IDENTIFICADOR e ANA_SENHA como secrets do ambiente, nunca no código.');process.exit(2);}
const request=async(url,headers)=>{
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),20000);
  try{
    const resp=await fetch(url,{headers,signal:controller.signal,redirect:'error'});
    if(!resp.ok)throw new Error('ANA HTTP '+resp.status);
    const json=await resp.json();
    if(json?.code && Number(json.code)>=400)throw new Error('API ANA retornou erro '+json.code);
    return json;
  }finally{clearTimeout(timer);}
};
try{
  const auth=await request(BASE+'/OAUth/v1',{'Identificador':id,'Senha':password,'Accept':'application/json'});
  const token=auth?.items?.tokenautenticacao ?? auth?.items?.tokenAutenticacao ?? auth?.tokenautenticacao;
  if(typeof token!=='string'||!token)throw new Error('Resposta de autenticação não reconhecida');
  const query=new URLSearchParams({
    'Código da Estação':code,
    'Tipo Filtro Data':'DATA_LEITURA',
    'Data de Busca (yyyy-MM-dd)':new Date().toISOString().slice(0,10),
    'Range Intervalo de busca':'DIAS_7'
  });
  const data=await request(BASE+'/HidroinfoanaSerieTelemetricaAdotada/v1?'+query.toString(),{
    'Authorization':'Bearer '+token,
    'Accept':'application/json'
  });
  const records=Array.isArray(data?.items)?data.items:[];
  // Não imprimir token, CPF, senha, cabeçalhos, ou payload bruto nos logs.
  console.log(JSON.stringify({source:'ANA HidroWebService',endpoint:'HidroinfoanaSerieTelemetricaAdotada/v1',station_code:code,records_returned:records.length,api_status:data?.code??null,checked_at:new Date().toISOString(),ready_for_mapping:records.length>0}));
}catch(e){
  // Nunca imprimir objeto Error completo: algumas bibliotecas incluem URLs/cabeçalhos.
  console.error('Consulta ANA falhou: '+String(e?.message||'erro').replace(/\d{11}/g,'[identificador]'));
  process.exitCode=1;
}
