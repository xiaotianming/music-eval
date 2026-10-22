import {fmt, type OverallScore as Score} from './api';
import './overall-score.css';

export function OverallScore({value, compact=false}: {value?:Score; compact?:boolean}) {
  if (!value) return <span className="muted">—</span>;
  const complete=value.status==='complete';
  const caption=value.status==='invalid'?'不可评分':value.score==null?'待评分':complete?'综合评分':'暂定分';
  if (compact) return <span className={'overall-compact '+(complete?'':'partial')} title={value.reason||`${caption}，已覆盖 ${value.coverage}% 权重`}>
    <strong>{fmt(value.score,1)}</strong><small>/100</small>{!complete&&<em>{caption}</em>}
  </span>;
  return <section className={'overall-panel '+(complete?'':'partial')} aria-label="综合评分及构成">
    <div className="overall-heading"><div><h3>{caption}</h3><p>已覆盖 {value.coverage}% 权重{value.exploratory?' · 纯音乐美学为探索性结果':''}</p></div>
      <div className="overall-number"><strong>{fmt(value.score,1)}</strong><span>/ 100</span></div>
    </div>
    <p className="overall-rule">音乐美学 70% · 提示词匹配 20% · 音频健康 10%</p>
    {value.reason&&<p className="overall-missing">{value.reason}</p>}
    {value.missing.length>0&&<p className="overall-missing">缺少{value.missing.join('、')}。暂定分按已完成项目权重换算，补齐后更新。</p>}
    <details><summary>查看评分构成与规则</summary>
      <div className="table-scroll"><table><thead><tr><th>项目</th><th>分项 /100</th><th>实际权重</th><th>计入总分</th></tr></thead>
        <tbody>{value.components.map(c=><tr key={c.id}><td>{c.label}</td><td>{fmt(c.score,2)}</td><td>{fmt(c.effective_weight*100,1)}%</td><td>{c.score==null?'—':fmt(c.contribution,2)}</td></tr>)}</tbody>
      </table></div>
      {value.components.filter(c=>c.reason).map(c=><p className="overall-missing" key={c.id}>{c.label}：{c.reason}</p>)}
      <p>美学取适用维度均值 ÷ 5 × 100；CLAP 取非负余弦值 × 100。音频健康按近满幅和静音比例扣分，具体公式见评估协议。</p>
      <small>{value.version} · 项目自定义评分；完整评分参与模型汇总，FAD 单独报告。</small>
    </details>
  </section>;
}
