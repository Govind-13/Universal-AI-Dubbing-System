const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data'); // node's form-data

async function test() {
  try {
      const formData = new FormData()
      formData.append('file', fs.createReadStream('../backend/test_with_audio.mp4'))

      const response = await axios.post(
        `http://localhost:8000/upload?target_language=hi`,
        formData,
        {
          headers: {
            // Force this exactly like App.jsx:
            'Content-Type': 'multipart/form-data',
          },
        }
      )
      console.log('Success!', response.data);
  } catch (error) {
      console.error('Error!', error.message);
      if (error.response) console.error(error.response.data);
  }
}
test();
