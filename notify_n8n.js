import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = 'https://dmpguhooyvgmotwpffhn.supabase.co'
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtcGd1aG9veXZnbW90d3BmZmhuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTQ4OTQzMSwiZXhwIjoyMDY1MDY1NDMxfQ.Dm9OM9zvKTu41hvh10Qoj8c0fY7HxrEPHKEiuaxgxTE' // Use service role key (from Supabase > Settings > API)
const N8N_WEBHOOK_URL = 'http://localhost:5678/webhook/new-resident-welcome'

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const insertAndNotify = async () => {
  const { data, error } = await supabase.from('new_residents').insert([
    {
      full_name: 'Real Fun Guy',
      email: 'erock8712@gmail.com',
      address: '111 Main St'
    }
  ]).select()

  if (error) {
    console.error('Insert failed:', error)
    return
  }

  const newResident = data[0]

  console.log("🚀 Sending to n8n:", newResident);

  const res = await fetch(N8N_WEBHOOK_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(newResident)
  })

  const responseText = await res.text()
  console.log('📨 n8n response status:', res.status)
  console.log('📨 n8n response body:', responseText)
}

insertAndNotify()
