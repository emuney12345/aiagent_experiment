FROM node:18

# Create app directory
WORKDIR /usr/src/app

# Copy package files and install
COPY package*.json ./
RUN npm install

# Copy the rest of the source code
COPY . .

# Expose port
EXPOSE 3000

# Start the app
CMD ["npm", "run", "start"]
