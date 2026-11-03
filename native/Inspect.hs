{-# LANGUAGE OverloadedStrings #-}
import qualified Dhall.Core as C
import qualified Dhall.Parser as P
import qualified Dhall.Import as I
import qualified Dhall.Crypto as Crypto
import Data.Aeson
import qualified Data.ByteString.Lazy.Char8 as B
import Data.Text (Text)
import qualified Data.Text.IO as T
import Data.Foldable (toList)
import Control.Monad.Trans.State.Strict (execStateT)
import System.Environment
import System.FilePath
import Prettyprinter
import Prettyprinter.Render.Text (renderStrict)

render :: Pretty a => a -> Text
render = renderStrict . layoutPretty defaultLayoutOptions . pretty
main = do
  args <- getArgs
  let (syntaxOnly,file) = case args of
        ["--syntax",file] -> (True,file)
        [file] -> (False,file)
        _ -> error "Expected [--syntax] FILE"
  text <- T.readFile file
  expression <- either (fail . show) pure (P.exprFromText file text)
  status <- if syntaxOnly then pure (I.emptyStatus (takeDirectory file)) else execStateT (I.loadWith expression) (I.emptyStatus (takeDirectory file))
  edges <- mapM edge (I._graph status)
  imports <- mapM record (toList expression)
  B.putStrLn $ encode $ object ["imports" .= imports, "graph" .= edges]
  where
    edge e = do
      parent <- record (I.chainedImport (I.parent e))
      child <- record (I.chainedImport (I.child e))
      pure $ object ["parent" .= parent, "child" .= child]
    record i = do
      fields <- case C.importType (C.importHashed i) of
        C.Remote url -> pure ["type" .= ("remote"::String), "url" .= render url, "headers" .= maybe False (const True) (C.headers url)]
        C.Local prefix file -> do
          path <- I.localToPath prefix file
          pure ["type" .= ("local"::String), "path" .= path]
        C.Env name -> pure ["type" .= ("environment"::String), "name" .= name]
        C.Missing -> pure ["type" .= ("missing"::String)]
      pure $ object $ ["expression" .= render i, "mode" .= show (C.importMode i), "hash" .= fmap Crypto.toString (C.hash (C.importHashed i))] ++ fields
