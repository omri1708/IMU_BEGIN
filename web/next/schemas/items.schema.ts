import { z } from 'zod'
export const ItemsSchema = z.object({
  name: z.string().min(2,'לפחות 2 תווים').max(40,'מקסימום 40'),
  description: z.string().max(200,'מקסימום 200').optional()
})
export type ItemsInput = z.infer<typeof ItemsSchema>
