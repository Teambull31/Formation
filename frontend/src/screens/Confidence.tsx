// « Sûr » ou « je devine » avant de répondre : une erreur sûre de soi revient le jour même, une réponse devinée ne compte pas comme sue.
export default function Confidence({ value, onChange }: { value: boolean | null; onChange: (v: boolean | null) => void }) {
  return (
    <div className="row" role="group" aria-label="Confiance">
      <span className="tag">Avant de répondre :</span>
      <button className="chip" aria-pressed={value === true} onClick={() => onChange(value === true ? null : true)}>Sûr</button>
      <button className="chip" aria-pressed={value === false} onClick={() => onChange(value === false ? null : false)}>Je devine</button>
    </div>
  )
}

export const sureWrongNote = 'Erreur commise en étant sûr de toi : lis bien l\'explication, la question revient aujourd\'hui.'
