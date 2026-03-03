import { sendNotification } from '@/app/actions'

export async function POST(req: Request) {
  try {
    const { message } = await req.json()

    if (!message) {
      return Response.json(
        { error: 'message is required' },
        { status: 400 }
      )
    }

    const result = await sendNotification(message)
    return Response.json(result)
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    console.error('API error:', errorMsg, error)
    return Response.json(
      { error: errorMsg },
      { status: 500 }
    )
  }
}
