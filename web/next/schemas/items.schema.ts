import { z } from 'zod'
export const ItemsSchema = z.object({
  name: z.string().optional(),
  description: z.string().optional()
})
export type ItemsInput = z.infer<typeof ItemsSchema>
