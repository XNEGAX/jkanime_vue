import { registerPlugin } from '@capacitor/core'

const TvKeyboard = registerPlugin('TvKeyboard')

export async function showTvKeyboard() {
  try {
    await TvKeyboard.show()
  } catch {
    // En navegador normal el teclado depende del sistema operativo.
  }
}

export async function editTvValue(options) {
  try {
    return await TvKeyboard.edit(options)
  } catch {
    return { cancelled: true }
  }
}
