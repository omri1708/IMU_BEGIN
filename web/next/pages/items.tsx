import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { useRole, canEdit, canView } from '../lib/rbac'
import { Field } from '../components/Field'

// שים לב לנתיב: pages/ -> ../schemas ; קובץ הסכימה שנוצר: web/next/schemas/items.schema.ts
import { ItemsSchema } from '../schemas/items.schema'

// rbac.json נמצא ב־web/policy, ולכן מ־pages צריך ../../policy
import rbac from '../../policy/rbac.json'

export default function ItemsForm() {
  const role = useRole()
  const Schema = ItemsSchema
  type FormT = z.infer<typeof Schema>

  const { register, handleSubmit, reset, formState: { errors } } =
    useForm<FormT>({ resolver: zodResolver(Schema) })

  const onSubmit = async (data: FormT) => {
    const res = await fetch('/api/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    if (res.ok) reset()
  }

  return (
    <main style={{ maxWidth: 640, margin: '40px auto', fontFamily: 'system-ui' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>Items — טופס</h1>

      <form onSubmit={handleSubmit(onSubmit)}>
        {canView(role, 'items', 'name', rbac) && (
          <Field
            label='name'
            name='name'
            register={register}
            errors={errors}
            disabled={!canEdit(role, 'items', 'name', rbac)}
          />
        )}

        {canView(role, 'items', 'description', rbac) && (
          <Field
            label='description'
            name='description'
            register={register}
            errors={errors}
            disabled={!canEdit(role, 'items', 'description', rbac)}
          />
        )}

        <button type='submit' style={{ padding: '10px 16px', borderRadius: 8 }}>
          שמור
        </button>
      </form>
    </main>
  )
}
