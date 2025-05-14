# MySmiski 

MySmiski is a cute, AI-powered app for detecting and collecting Smiski figurines. Snap a photo, and we'll tell you which Smiski you found!

If you are unfamiliar with what Smiskis are, feel free to have a look [here](https://smiski.com/e/smiski/). I am not sponsored (though, I would not mind if they did) -- I am just a small Smiski collector who thought this would be a fun little project.

# Project Architecture 

This is a full-stack application with the following project structure and technologies:

- **Frontend**: Built with Next.js, Tailwind CSS, and Framer Motion for modern UI. 
- **Backend**: Django REST API for submitting photos and updating content 
- **Storage**: Locally, but will probably expand to incorporate AWS S3 

```
├── backend
│   ├── manage.py
│   └── mysmiski_api
├── frontend
│   ├── app
│   ├── eslint.config.mjs
│   ├── next-env.d.ts
│   ├── next.config.ts
│   ├── package-lock.json
│   ├── package.json
│   ├── postcss.config.mjs
│   ├── public
│   ├── README.md
│   └── tsconfig.json
├── README.md
└── structure.txt
```