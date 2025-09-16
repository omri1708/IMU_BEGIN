
let _role = 'admin' as 'admin'|'manager'|'user'
export function setRole(r:'admin'|'manager'|'user'){ _role = r }
export function useRole(){ return _role }
export function canView(role:string, entity:string, field?:string, rbac:any){
  const e = rbac.entities?.[entity] || {}
  const f = e.fields?.[field||''] || {}
  const allow = (f.visible || e.visible || rbac.entities?.default?.visible || [])
  return allow.includes(role)
}
export function canEdit(role:string, entity:string, field?:string, rbac:any){
  const e = rbac.entities?.[entity] || {}
  const f = e.fields?.[field||''] || {}
  const allow = (f.editable || e.editable || rbac.entities?.default?.editable || [])
  return allow.includes(role)
}
