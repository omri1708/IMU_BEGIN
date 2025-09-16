
import React from 'react'
export function Field({label, name, register, errors, disabled}:{label:string;name:string;register:any;errors:any;disabled?:boolean}){
  return <div style={{marginBottom:12, opacity: disabled?0.6:1}}>
    <label style={{display:'block',fontWeight:600}}>{label}</label>
    <input {...register(name)} disabled={disabled} style={{padding:8,border:'1px solid #ddd',borderRadius:8,width:'100%'}} />
    {errors?.[name] && <div style={{color:'crimson',fontSize:12}}>{String(errors[name].message||'שדה לא תקין')}</div>}
  </div>
}
