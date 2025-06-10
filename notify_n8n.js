import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = 'https://dmpguhooyvgmotwpffhn.supabase.co'
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtcGd1aG9veXZnbW90d3BmZmhuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTQ4OTQzMSwiZXhwIjoyMDY1MDY1NDMxfQ.Dm9OM9zvKTu41hvh10Qoj8c0fY7HxrEPHKEiuaxgxTE' // Use service role key (from Supabase > Settings > API)
const N8N_WEBHOOK_URL = 'http://localhost:5678/webhook/new-resident-welcome'

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const insertAndNotify = async () => {
  const { data, error } = await supabase.from('new_residents').insert([
    {
      full_name: 'Real Fun Guy',
      email: 'erock0898@gmail.com',
      address: '111 Main St'
    }
  ])

  .select()

  if (error) {
    console.error('Insert failed:', error)
    return
  }

  const newResident = data[0]

  const res = await fetch("http://localhost:5678/webhook/new-resident-welcome", {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(newResident)
  })

  console.log('n8n response status:', res.status)
}

insertAndNotify()
