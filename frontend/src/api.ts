export type MetricItem = {id:string; sample_id:string; metric:string; status:string; reason:string|null; stale?:boolean; elapsed:number|null; peak_mb:number|null; result:any; snapshot:any};
export type OverallScore = {version:string;max_score:number;score:number|null;status:'complete'|'partial'|'unavailable'|'invalid';coverage:number;missing:string[];reason:string|null;exploratory:boolean;description:string;components:{id:string;label:string;weight:number;effective_weight:number;score:number|null;contribution:number;reason:string|null}[]};
export type Sample = {id:string;filename:string;sha256:string;prompt_id:string;prompt:string;prompt_en:string;translation_source:string;model_id:string;model_version:string;audio_type:'song'|'instrumental';seed:string;tags:string;role:'generated'|'reference';results:Record<string,MetricItem>;overall?:OverallScore};
export type Job = {id:string;status:string;created:number;updated:number;done:number;total:number;items:MetricItem[];config:any;overall_scores?:Record<string,OverallScore>};
export const labels:Record<string,string> = {overall_score:'综合评分（100分）',basic:'基础检查',clap:'提示词匹配',songeval:'歌曲美学',fad:'批次 FAD',translation:'本地翻译',Coherence:'整体连贯性',Musicality:'音乐性',Memorability:'记忆度',Clarity:'结构清晰度',Naturalness:'人声自然度',silence_ratio:'静音比例',near_full_scale_ratio:'近满幅比例',loudness_lufs:'综合响度 LUFS',duration:'时长（秒）'};
export const states:Record<string,string> = {queued:'排队中',running:'运行中',success:'已完成',failed:'失败',skipped:'未计算',cancelled:'已取消',completed:'已完成',completed_with_errors:'部分失败',stale:'需要重算'};
export async function api<T=any>(path:string, options?:RequestInit):Promise<T>{
  const response = await fetch('/api'+path,options);
  if(!response.ok){let message=await response.text();try{const value=JSON.parse(message);message=typeof value.detail==='string'?value.detail:JSON.stringify(value.detail)}catch{}throw new Error(message)}
  return response.json();
}
export function post<T=any>(path:string,body?:any){return api<T>(path,{method:'POST',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined})}
export function valueOf(s:Sample,metric:string){const r=s.results[metric];return r?.status==='success'&&!r.stale?r.result?.value:null}
export const fmt = (n:number|null|undefined,d=3)=>n==null?'—':Number(n).toFixed(d);
