This explains how to use the confirm ui.
In order to use this, you will need to have imported ui

# Calling the ui
## Create a view object
```py
view = ui.Confirm()
```
## Send the confirm message. 
You can view the send function docstring for exact details on arguments
```py
await view.send()
```
## Wait for and use the response
You must wait for the seponse like this:
```py
await view.wait()
```
  
After that, you may use the response by looking at view.value  
The value of this will be one of the ConfirmResponse responses  
You can compare these to take actions based on the 3 respones, like so:
```py
if view.value is ui.ConfirmResponse.DENIED:
    Do stuff here
```
